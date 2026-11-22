"""M433: one-time taxonomy reclassification, never an FBX or Place migration.

The source_path belongs to the registered FBX revision and may legitimately
contain the old /bush/ directory. Moving it would invalidate authoring refs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time

from sqlite_connection import connect as connect_sqlite

# Only assets verified in the last authoring snapshot are migrated. No generic
# prefix rule: it must not unexpectedly reclassify unrelated future content.
_LEGACY_IVY = ('ivy_02', 'ivy_03', 'ivy_05')


def migrate_ivy_category(store) -> str | None:
    """Return backup path if rows changed; no-op on subsequent startups."""
    marks = ','.join('?' for _ in _LEGACY_IVY)
    with store.connect() as source:
        rows = source.execute(
            f"SELECT slug FROM location_assets WHERE slug IN ({marks}) AND category='bush'",
            _LEGACY_IVY,
        ).fetchall()
        if not rows:
            return None
        backup_dir = store.runtime / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_path = backup_dir / f'location_ivy_category_pre_m433_{stamp}.sqlite'
        with connect_sqlite(backup_path) as target:
            source.backup(target)

    # Keep both the identity and every publication/LOD/atlas reference stable.
    # Increment revision to invalidate stale Identity editor sessions.
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute(
            f"UPDATE location_assets SET category='ivy', revision=revision+1, updated_at=? "
            f"WHERE slug IN ({marks}) AND category='bush'",
            (time.time(), *_LEGACY_IVY),
        )
    return backup_path.relative_to(store.root).as_posix()
