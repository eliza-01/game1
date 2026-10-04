from __future__ import annotations

from pathlib import Path
import hashlib
import re
import shutil
import time

from animation_core.common import _binding_id, _canonical_file_stem, _clip_id

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ACTIVE_KEY = "active_character_archetype_id"


class CharacterIdentityService:
    """Rename/reclassify a character archetype without losing published asset ids.

    This migration owns the cross-domain identity change: character metadata,
    canonical model/animation paths, animation ids/bindings/publication history,
    and the active-character setting move together as one operation.
    """

    def __init__(self, root: Path, characters, animations):
        self.root = root.resolve()
        self.characters = characters
        self.animations = animations

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _relative(root: Path, path: Path) -> str:
        return path.resolve().relative_to(root).as_posix()

    @staticmethod
    def _animation_relative(race: str, gender: str, character_id: str, row: dict, suffix: str) -> Path:
        stem = _canonical_file_stem(
            str(row.get("scope") or ""),
            str(row.get("weapon_set") or ""),
            str(row.get("slot") or ""),
            int(row.get("variant") or 0),
        )
        if str(row.get("scope") or "") == "base":
            return Path("characters") / race / gender / character_id / "animations" / "base" / f"{stem}{suffix}"
        return (
            Path("characters")
            / race
            / gender
            / character_id
            / "animations"
            / "weapons"
            / str(row.get("weapon_set") or "")
            / f"{stem}{suffix}"
        )

    def _managed_file(self, stored_path: str, expected_root: Path) -> Path | None:
        value = str(stored_path or "").strip()
        if not value:
            return None
        path = (self.root / value).resolve()
        try:
            path.relative_to(expected_root.resolve())
        except ValueError as error:
            raise ValueError(f"managed asset path escaped the game1 project: {value}") from error
        return path

    def _copy_plan(self, moves: list[tuple[Path, Path]]) -> list[tuple[Path, Path, bool]]:
        copied: list[tuple[Path, Path, bool]] = []
        for source, target in moves:
            if source.resolve() == target.resolve():
                continue
            if not source.is_file():
                raise ValueError(f"cannot migrate missing canonical asset: {source.relative_to(self.root)}")
            target.parent.mkdir(parents=True, exist_ok=True)
            created = False
            if target.exists():
                if self._sha256(source) != self._sha256(target):
                    raise ValueError(f"identity migration target already contains different data: {target.relative_to(self.root)}")
            else:
                shutil.copy2(source, target)
                created = True
            copied.append((source, target, created))
        return copied

    @staticmethod
    def _rollback_copies(copied: list[tuple[Path, Path, bool]]) -> None:
        for _source, target, created in reversed(copied):
            if created:
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass

    @staticmethod
    def _cleanup_empty(path: Path, stop: Path) -> None:
        current = path.parent
        stop = stop.resolve()
        while current != stop and stop in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def update(self, old_character_id: str, payload: dict) -> dict:
        old_id = str(old_character_id or "").strip().lower()
        old = self.characters.get(old_id)
        if not old:
            raise ValueError(f"unknown character archetype: {old_id}")

        options = self.characters.options()
        race = str(payload.get("race", old.get("race") or "") or "").strip().lower()
        gender = str(payload.get("gender", old.get("gender") or "") or "").strip().lower()
        new_id = str(payload.get("id", old_id) or old_id).strip().lower()
        display_name = str(payload.get("displayName", old.get("display_name") or "") or "").strip()

        if race not in set(options.get("races") or []):
            raise ValueError("race must be selected from the registered race pool: " + ", ".join(options.get("races") or []))
        if gender not in set(options.get("genders") or []):
            raise ValueError("gender must be male or female")
        if not ID_RE.fullmatch(new_id):
            raise ValueError("id must match [a-z0-9][a-z0-9_-]{0,63}")
        if not display_name:
            display_name = f"{race.title()} {gender.title()}"

        source_root = self.root / "assets/source/characters"
        prepared_root = self.root / "assets/prepared/characters"
        old_source = self._managed_file(str(old.get("source_path") or ""), source_root)
        old_prepared = self._managed_file(str(old.get("prepared_path") or ""), prepared_root)
        new_source = (
            self.root / "assets/source/characters" / race / gender / new_id / "model" / old_source.name
            if old_source else None
        )
        new_prepared = (
            self.root / "assets/prepared/characters" / race / gender / new_id / "model" / old_prepared.name
            if old_prepared else None
        )

        with self.characters.connect() as connection:
            id_conflict = connection.execute(
                "SELECT id FROM characters WHERE id=? AND id<>?",
                (new_id, old_id),
            ).fetchone()
            if id_conflict:
                raise ValueError(f"archetype id is already registered: {new_id}")
            identity_conflict = connection.execute(
                "SELECT id FROM characters WHERE race=? AND gender=? AND id<>?",
                (race, gender, old_id),
            ).fetchone()
            if identity_conflict:
                raise ValueError(f"{race}/{gender} is already registered as {identity_conflict['id']}")

            animation_rows = [
                dict(row)
                for row in connection.execute(
                    """SELECT c.id AS old_clip_id,c.source_path,c.prepared_path,
                              b.id AS old_binding_id,b.scope,b.weapon_set,b.slot,b.variant
                       FROM animation_clips c
                       JOIN animation_bindings b ON b.clip_id=c.id
                       WHERE c.character_id=? AND b.character_id=?
                       ORDER BY b.scope,b.weapon_set,b.slot,b.variant""",
                    (old_id, old_id),
                )
            ]

        moves: list[tuple[Path, Path]] = []
        if old_source and new_source:
            moves.append((old_source, new_source))
        if old_prepared and new_prepared:
            moves.append((old_prepared, new_prepared))

        animation_migrations: list[dict] = []
        for row in animation_rows:
            old_animation_source = self._managed_file(str(row.get("source_path") or ""), source_root)
            old_animation_prepared = self._managed_file(str(row.get("prepared_path") or ""), prepared_root)
            source_suffix = old_animation_source.suffix.lower() if old_animation_source else ".rbxm"
            prepared_suffix = old_animation_prepared.suffix.lower() if old_animation_prepared else source_suffix
            source_relative = self._animation_relative(race, gender, new_id, row, source_suffix)
            prepared_relative = self._animation_relative(race, gender, new_id, row, prepared_suffix)
            target_source = self.root / "assets/source" / source_relative
            target_prepared = self.root / "assets/prepared" / prepared_relative
            if old_animation_source:
                moves.append((old_animation_source, target_source))
            if old_animation_prepared:
                moves.append((old_animation_prepared, target_prepared))
            new_clip_id = _clip_id(new_id, row["scope"], row["weapon_set"], row["slot"], int(row["variant"]))
            new_binding_id = _binding_id(new_id, row["scope"], row["weapon_set"], row["slot"], int(row["variant"]))
            animation_migrations.append(
                {
                    **row,
                    "new_clip_id": new_clip_id,
                    "new_binding_id": new_binding_id,
                    "new_source_path": target_source.relative_to(self.root).as_posix(),
                    "new_prepared_path": target_prepared.relative_to(self.root).as_posix(),
                }
            )

        copied = self._copy_plan(moves)
        now = time.time()
        try:
            with self.characters.connect() as connection:
                for row in animation_migrations:
                    if row["new_clip_id"] != row["old_clip_id"]:
                        collision = connection.execute(
                            "SELECT id FROM animation_clips WHERE id=? AND id<>?",
                            (row["new_clip_id"], row["old_clip_id"]),
                        ).fetchone()
                        if collision:
                            raise ValueError(f"animation clip id collision during archetype edit: {row['new_clip_id']}")
                    if row["new_binding_id"] != row["old_binding_id"]:
                        collision = connection.execute(
                            "SELECT id FROM animation_bindings WHERE id=? AND id<>?",
                            (row["new_binding_id"], row["old_binding_id"]),
                        ).fetchone()
                        if collision:
                            raise ValueError(f"animation binding id collision during archetype edit: {row['new_binding_id']}")

                connection.execute(
                    """UPDATE characters
                       SET id=?,display_name=?,race=?,gender=?,source_path=?,prepared_path=?,revision=revision+1,updated_at=?
                       WHERE id=?""",
                    (
                        new_id,
                        display_name,
                        race,
                        gender,
                        self._relative(self.root, new_source) if new_source else str(old.get("source_path") or ""),
                        self._relative(self.root, new_prepared) if new_prepared else str(old.get("prepared_path") or ""),
                        now,
                        old_id,
                    ),
                )
                connection.execute("UPDATE character_publications SET character_id=? WHERE character_id=?", (new_id, old_id))
                connection.execute("UPDATE project_settings SET value=? WHERE key=? AND value=?", (new_id, ACTIVE_KEY, old_id))
                connection.execute("UPDATE animation_profiles SET character_id=?,updated_at=? WHERE character_id=?", (new_id, now, old_id))

                for row in animation_migrations:
                    connection.execute(
                        "UPDATE animation_publications SET clip_id=? WHERE clip_id=?",
                        (row["new_clip_id"], row["old_clip_id"]),
                    )
                    connection.execute(
                        """UPDATE animation_clips
                           SET id=?,character_id=?,source_path=?,prepared_path=?,updated_at=?
                           WHERE id=?""",
                        (
                            row["new_clip_id"],
                            new_id,
                            row["new_source_path"],
                            row["new_prepared_path"],
                            now,
                            row["old_clip_id"],
                        ),
                    )
                    connection.execute(
                        """UPDATE animation_bindings
                           SET id=?,character_id=?,clip_id=?,updated_at=?
                           WHERE id=?""",
                        (
                            row["new_binding_id"],
                            new_id,
                            row["new_clip_id"],
                            now,
                            row["old_binding_id"],
                        ),
                    )
        except Exception:
            self._rollback_copies(copied)
            raise

        for source, target, _created in copied:
            if source.resolve() == target.resolve():
                continue
            try:
                source.unlink(missing_ok=True)
                stop = source_root if source_root in source.parents else prepared_root
                self._cleanup_empty(source, stop)
            except Exception:
                pass

        self.characters.export()
        self.animations.export()
        updated = self.characters.get(new_id)
        return {
            "character": updated,
            "oldId": old_id,
            "newId": new_id,
            "identityChanged": any(
                [
                    old_id != new_id,
                    str(old.get("race") or "") != race,
                    str(old.get("gender") or "") != gender,
                ]
            ),
            "migratedAnimationClips": len(animation_migrations),
            "migratedFiles": len(copied),
            "studioSyncRequired": bool(updated and updated.get("model_asset_id")),
        }
