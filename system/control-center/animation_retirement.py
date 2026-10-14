"""Archive retired animation registrations without touching Roblox Cloud assets.

A removed binding must not be able to revive a published clip/asset ID when
its original source file is encountered by a subsequent folder scan. This is
a registry lifecycle concern, not a publication or file-deletion operation.
"""
from __future__ import annotations

import json
import time


_TABLES = {
    "character": ("animation_clips", "animation_bindings", "animation_publications"),
    "monster": ("monster_animation_clips", "monster_animation_bindings", "monster_animation_publications"),
    "npc": ("monster_animation_clips", "monster_animation_bindings", "monster_animation_publications"),
}


def _tables(kind: str) -> tuple[str, str, str]:
    try:
        return _TABLES[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported animation registration kind: {kind}") from exc


def ensure_archive(connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS animation_registration_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            clip_id TEXT NOT NULL,
            asset_id TEXT NOT NULL DEFAULT '',
            clip_json TEXT NOT NULL,
            publications_json TEXT NOT NULL,
            retired_at REAL NOT NULL
        )
    """)


def retire_unbound_clip(connection, kind: str, clip_id: str) -> bool:
    """Atomically archive and remove an unbound clip and its publication links.

    Raw animation files are never removed. The archived publication records
    preserve their permanent Roblox IDs but cannot participate in a new scan.
    """
    clips, bindings, publications = _tables(kind)
    if connection.execute(f"SELECT 1 FROM {bindings} WHERE clip_id=? LIMIT 1", (clip_id,)).fetchone():
        return False
    row = connection.execute(f"SELECT * FROM {clips} WHERE id=?", (clip_id,)).fetchone()
    history = [dict(r) for r in connection.execute(
        f"SELECT * FROM {publications} WHERE clip_id=? ORDER BY id", (clip_id,)
    )]
    if row is None and not history:
        return False
    ensure_archive(connection)
    clip = dict(row) if row is not None else {}
    connection.execute(
        """INSERT INTO animation_registration_archive
           (kind,clip_id,asset_id,clip_json,publications_json,retired_at)
           VALUES(?,?,?,?,?,?)""",
        (
            kind, clip_id, str(clip.get("asset_id") or ""),
            json.dumps(clip, ensure_ascii=False),
            json.dumps(history, ensure_ascii=False), time.time(),
        ),
    )
    connection.execute(f"DELETE FROM {publications} WHERE clip_id=?", (clip_id,))
    connection.execute(f"DELETE FROM {clips} WHERE id=?", (clip_id,))
    return True


def retire_legacy_orphans(connection, kind: str) -> int:
    """Migrate orphaned records left by older Remove implementations.

    This is deliberately limited to clips with no active binding and to
    history rows whose clip is already missing. Active clips are untouched.
    """
    clips, bindings, publications = _tables(kind)
    ids = [str(r[0]) for r in connection.execute(
        f"SELECT c.id FROM {clips} c WHERE NOT EXISTS "
        f"(SELECT 1 FROM {bindings} b WHERE b.clip_id=c.id)"
    )]
    ids.extend(str(r[0]) for r in connection.execute(
        f"SELECT DISTINCT p.clip_id FROM {publications} p "
        f"WHERE NOT EXISTS (SELECT 1 FROM {clips} c WHERE c.id=p.clip_id)"
    ))
    count = 0
    for clip_id in dict.fromkeys(ids):
        count += retire_unbound_clip(connection, kind, clip_id)
    return count
