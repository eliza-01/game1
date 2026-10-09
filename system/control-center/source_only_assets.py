from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3

IGNORE = {".gitkeep", "desktop.ini"}
PATH_COLUMNS = (
    ("characters", "source_path", "sha256"),
    ("characters", "prepared_path", "sha256"),
    ("animation_clips", "source_path", "source_sha256"),
    ("animation_clips", "prepared_path", "sha256"),
    ("weapons", "model_source_path", "model_sha256"),
    ("weapons", "model_prepared_path", "model_sha256"),
    ("weapon_textures", "source_path", "sha256"),
    ("weapon_textures", "prepared_path", "sha256"),
    ("monsters", "model_source_path", "model_sha256"),
    ("monsters", "model_prepared_path", "model_sha256"),
    ("monster_textures", "source_path", "sha256"),
    ("monster_textures", "prepared_path", "sha256"),
    ("monster_animation_clips", "source_path", "source_sha256"),
    ("monster_animation_clips", "prepared_path", "sha256"),
)
REWRITE_COLUMNS = (
    ("characters", "source_path"), ("characters", "prepared_path"),
    ("animation_clips", "source_path"), ("animation_clips", "prepared_path"),
    ("weapons", "model_source_path"), ("weapons", "model_prepared_path"),
    ("weapon_textures", "source_path"), ("weapon_textures", "prepared_path"),
    ("monsters", "model_source_path"), ("monsters", "model_prepared_path"),
    ("monster_textures", "source_path"), ("monster_textures", "prepared_path"),
    ("monster_animation_clips", "source_path"), ("monster_animation_clips", "prepared_path"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.DatabaseError:
        return set()


def _expected_hashes(connection: sqlite3.Connection) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, path_column, hash_column in PATH_COLUMNS:
        if table not in tables:
            continue
        columns = _columns(connection, table)
        if path_column not in columns or hash_column not in columns:
            continue
        for path_value, digest in connection.execute(
            f"SELECT {path_column},{hash_column} FROM {table} WHERE COALESCE({path_column},'')<>''"
        ):
            path_value = str(path_value or "").replace("\\", "/")
            digest = str(digest or "").lower()
            if path_value and digest:
                result.setdefault(path_value, set()).add(digest)
    return result


def _rewrite_value(value):
    if isinstance(value, str):
        return value.replace("assets/prepared/", "assets/source/").replace("assets\\prepared\\", "assets\\source\\")
    if isinstance(value, list):
        return [_rewrite_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_value(item) for key, item in value.items()}
    return value


def _remove_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    try:
        root.rmdir()
    except OSError:
        pass


def migrate_source_only_assets(project_root: Path, db_path: Path) -> dict | None:
    project_root = project_root.resolve()
    assets = project_root / "assets"
    source_root = assets / "source"
    prepared_root = assets / "prepared"
    manifests = assets / "manifests"
    reports = assets / "reports"

    prepared_files = []
    if prepared_root.exists():
        prepared_files = sorted(
            [p for p in prepared_root.rglob("*") if p.is_file() and p.name.lower() not in IGNORE],
            key=lambda p: p.as_posix().casefold(),
        )

    legacy_db_paths = False
    if db_path.is_file():
        with sqlite3.connect(db_path) as connection:
            tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table, column in REWRITE_COLUMNS:
                if table not in tables or column not in _columns(connection, table):
                    continue
                if connection.execute(
                    f"SELECT 1 FROM {table} WHERE {column} LIKE 'assets/prepared/%' LIMIT 1"
                ).fetchone():
                    legacy_db_paths = True
                    break

    legacy_manifest_paths = False
    if manifests.exists():
        for path in manifests.glob("*.json"):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if "assets/prepared/" in text or "assets\\prepared\\" in text:
                legacy_manifest_paths = True
                break

    if not prepared_files and not legacy_db_paths and not legacy_manifest_paths:
        if prepared_root.exists():
            _remove_tree(prepared_root)
        return None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = assets / "reimported" / "source-only-migration" / stamp
    backup_root.mkdir(parents=True, exist_ok=True)
    if db_path.is_file():
        shutil.copy2(db_path, backup_root / "game1.db.before")
    if manifests.exists():
        shutil.copytree(manifests, backup_root / "manifests-before", dirs_exist_ok=True)
    if prepared_root.exists():
        shutil.copytree(prepared_root, backup_root / "prepared-before", dirs_exist_ok=True)

    expected: dict[str, set[str]] = {}
    if db_path.is_file():
        with sqlite3.connect(db_path) as connection:
            expected = _expected_hashes(connection)

    source_root.mkdir(parents=True, exist_ok=True)
    moved = 0
    deduped = 0
    prepared_wins = 0
    source_wins = 0
    conflict_records: list[dict] = []
    unresolved: list[str] = []

    plan: list[tuple[Path, Path, str]] = []
    for old in prepared_files:
        relative = old.relative_to(prepared_root)
        new = source_root / relative
        if not new.exists():
            plan.append((old, new, "move"))
            continue
        if not new.is_file():
            unresolved.append(f"canonical destination is not a file: {relative.as_posix()}")
            continue
        old_sha = sha256(old)
        new_sha = sha256(new)
        if old_sha == new_sha:
            plan.append((old, new, "dedupe"))
            continue

        old_key = old.relative_to(project_root).as_posix()
        new_key = new.relative_to(project_root).as_posix()
        old_expected = expected.get(old_key, set())
        new_expected = expected.get(new_key, set())
        old_active = old_sha in old_expected
        new_active = new_sha in new_expected
        any_reference = bool(old_expected or new_expected)

        if old_active:
            mode = "prepared-wins"
        elif new_active:
            mode = "source-wins"
        elif any_reference:
            unresolved.append(
                f"active metadata does not match either copy: {relative.as_posix()}"
            )
            continue
        else:
            # An orphaned legacy conflict has no authority in active metadata.
            # Preserve both in the migration backup and keep the canonical Source copy.
            mode = "source-wins"
        plan.append((old, new, mode))
        conflict_records.append({
            "path": relative.as_posix(),
            "resolution": mode,
            "sourceSha256": new_sha,
            "preparedSha256": old_sha,
            "referenced": any_reference,
        })

    if unresolved:
        raise RuntimeError("Source-only migration aborted before changes:\n- " + "\n- ".join(unresolved))

    for old, new, mode in plan:
        new.parent.mkdir(parents=True, exist_ok=True)
        if mode == "move":
            shutil.move(str(old), str(new))
            moved += 1
        elif mode == "dedupe":
            old.unlink(missing_ok=True)
            deduped += 1
        elif mode == "prepared-wins":
            shutil.copy2(old, new)
            old.unlink(missing_ok=True)
            prepared_wins += 1
        elif mode == "source-wins":
            old.unlink(missing_ok=True)
            source_wins += 1

    if db_path.is_file():
        with sqlite3.connect(db_path) as connection:
            tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table, column in REWRITE_COLUMNS:
                if table not in tables or column not in _columns(connection, table):
                    continue
                connection.execute(
                    f"UPDATE {table} SET {column}=REPLACE({column}, 'assets/prepared/', 'assets/source/') "
                    f"WHERE {column} LIKE 'assets/prepared/%'"
                )
            for table in ("animation_clips", "monster_animation_clips"):
                columns = _columns(connection, table)
                if {"sha256", "source_sha256"}.issubset(columns):
                    connection.execute(f"UPDATE {table} SET source_sha256=sha256")

    rewritten_manifests = 0
    if manifests.exists():
        for path in manifests.glob("*.json"):
            try:
                before = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            after = _rewrite_value(before)
            if after != before:
                path.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
                rewritten_manifests += 1

    _remove_tree(prepared_root)
    if prepared_root.exists():
        remaining = [p for p in prepared_root.rglob("*") if p.is_file()]
        if remaining:
            raise RuntimeError(f"assets/prepared still contains {len(remaining)} file(s) after migration")
        _remove_tree(prepared_root)

    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "schemaVersion": 1,
        "migration": "game1-source-only-assets-v1",
        "completedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "movedPreparedOnlyFiles": moved,
        "removedIdentityDuplicates": deduped,
        "preparedWins": prepared_wins,
        "sourceWins": source_wins,
        "conflicts": conflict_records,
        "rewrittenManifestFiles": rewritten_manifests,
        "backupPath": backup_root.relative_to(project_root).as_posix(),
    }
    (reports / f"source-only-migration-{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report
