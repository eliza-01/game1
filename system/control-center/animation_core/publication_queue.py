"""Read-only queue discovery for unpublished Character and Common animation clips.

The queue is a projection of authoritative clip/binding state, not a second
publication registry. Individual uploads still use publish_clip validation.
"""
from __future__ import annotations

from contextlib import closing


class AnimationPublicationQueueMixin:
    def pending_publications(self) -> list[dict]:
        with closing(self.connect()) as connection:
            rows = connection.execute("""
                SELECT c.id AS clip_id, c.name, c.character_id, c.asset_id,
                       c.source_path, c.prepared_path, c.sha256,
                       b.scope, b.weapon_set, b.slot, b.variant
                  FROM animation_clips c
                  JOIN animation_bindings b ON b.clip_id = c.id
                 WHERE (c.asset_id IS NULL OR TRIM(c.asset_id) = '')
                   AND c.prepared_path <> ''
                   AND c.source_path NOT LIKE '%.animation.json'
                 ORDER BY CASE WHEN c.character_id LIKE '%_common' THEN 0 ELSE 1 END,
                          c.character_id, b.scope, b.slot, b.variant, c.id
            """).fetchall()
        seen = set()
        result = []
        for raw in rows:
            row = dict(raw)
            clip_id = str(row['clip_id'])
            if clip_id in seen:
                continue
            seen.add(clip_id)
            result.append({
                'clipId': clip_id,
                'name': str(row['name']),
                'characterId': str(row['character_id']),
                'scope': str(row['scope']),
                'slot': str(row['slot']),
                'variant': int(row['variant'] or 1),
                'status': 'LOCAL_ONLY',
            })
        return result
