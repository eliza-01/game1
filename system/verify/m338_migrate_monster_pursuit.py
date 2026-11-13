"""M338: migrate monster pursuit radius into the per-species behavior registry.

Back up the local SQLite DB and generated manifests before touching them. The
old per-spawn monster home leash is dropped; NPC home-radius data is untouched.
Idempotent: reruns keep the previously configured per-species pursuit radius.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system" / "control-center"))
from monster_store import MonsterStore  # noqa: E402
from monster_spawn_store import MonsterSpawnStore  # noqa: E402


def run(root: Path = ROOT) -> Path:
    root = root.resolve()
    db = root / ".control-center/game1.db"
    if not db.is_file():
        raise FileNotFoundError(f"Monster DB missing: {db}. Migration aborted without overwriting registries.")
    manifest = root / "assets/manifests/monster-spawns.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"Monster spawn manifest missing: {manifest}")

    source = json.loads(manifest.read_text(encoding="utf-8"))
    if source.get("project") != "game1" or not isinstance(source.get("records"), dict):
        raise ValueError("Unrecognized monster spawn manifest; nothing changed")

    backup = root / (".m338_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    backup.mkdir(parents=True)
    with sqlite3.connect(db) as live, sqlite3.connect(backup / "game1.db") as saved:
        live.backup(saved)
    files = (
        "assets/manifests/monsters.json",
        "assets/manifests/monster-spawns.json",
        "src/shared/monster/MonsterRegistry.luau",
        "src/server/monster/MonsterSpawnRegistry.luau",
    )
    for relative in files:
        current = root / relative
        if current.is_file():
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, destination)

    # Existing species (including published model/texture IDs) come from the
    # authoritative SQLite store, never from reconstructed or sample values.
    removed = 0
    try:
        MonsterStore(root, kind="monster")
        for record in source["records"].values():
            if "homeRadiusStuds" in record:
                record.pop("homeRadiusStuds")
                removed += 1
        if removed:
            manifest.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        MonsterSpawnStore(root, None, None, None, kind="monster")
    except Exception:
        # A partial migration must not leave database and generated registries
        # out of sync. Restore from the SQLite online backup and file snapshots.
        with sqlite3.connect(backup / "game1.db") as saved, sqlite3.connect(db) as live:
            saved.backup(live)
        for relative in files:
            snapshot = backup / relative
            if snapshot.is_file():
                shutil.copy2(snapshot, root / relative)
        raise
    print(f"M338: species pursuit registry updated; removed {removed} monster spawn leash(es); backup: {backup}")
    return backup


if __name__ == "__main__":
    run()
