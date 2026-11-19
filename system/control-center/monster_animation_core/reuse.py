"""NPC animation reuse: multiple actor bindings can reference one published clip.

Ownership stays with the source NPC; the destination owns only its binding options.
No RBXM copies, publication records, or duplicate asset IDs are generated.
"""
from __future__ import annotations

import time

from npc_animation_taxonomy import WEAPON_SETS


MAX_CONNECT_ACTIONS = 100


class NpcAnimationReuseMixin:
    def connect_existing(self, target_npc: str, source_npc: str, binding_ids: object) -> dict:
        if self.kind != 'npc':
            raise ValueError('connect existing animations is only supported for NPCs')
        target_npc = str(target_npc or '').strip().lower()
        source_npc = str(source_npc or '').strip().lower()
        if not target_npc or not source_npc or target_npc == source_npc:
            raise ValueError('choose two different registered NPCs')
        if (not isinstance(binding_ids, list) or not 1 <= len(binding_ids) <= MAX_CONNECT_ACTIONS
                or any(not isinstance(key, str) or not key or len(key) > 256 for key in binding_ids)
                or len(set(binding_ids)) != len(binding_ids)):
            raise ValueError('select 1..100 distinct source animation actions')

        # One transaction: either all requested actions are linked or none are.
        # Never update a target's existing authored animation implicitly.
        with self.connect() as db:
            actors = {str(row['slug']): dict(row) for row in db.execute(
                'SELECT slug,skeleton_structure_signature FROM monsters WHERE slug IN (?,?)',
                (target_npc, source_npc),
            )}
            if target_npc not in actors or source_npc not in actors:
                raise ValueError('unknown NPC source or destination')
            rows = [dict(row) for row in db.execute(
                """SELECT b.*,c.monster_slug AS clip_owner,c.asset_id,c.sha256,c.published_sha256
                   FROM monster_animation_bindings b
                   JOIN monster_animation_clips c ON c.id=b.clip_id
                   WHERE b.monster_slug=?""", (source_npc,),
            )]
            available = {row['id']: row for row in rows
                         if row['clip_owner'] == source_npc
                         and str(row.get('asset_id') or '').isdigit()
                         and str(row.get('published_sha256') or '') == str(row.get('sha256') or '')}
            chosen = []
            for key in binding_ids:
                source = available.get(key)
                if source is None:
                    raise ValueError('source animation is missing, unpublished or changed: ' + key)
                if source['weapon_set'] not in WEAPON_SETS:
                    raise ValueError('source animation has an unsupported equipment type')
                occupied = db.execute(
                    """SELECT 1 FROM monster_animation_bindings
                       WHERE monster_slug=? AND weapon_set=? AND slot=? AND variant=?""",
                    (target_npc, source['weapon_set'], source['slot'], source['variant']),
                ).fetchone()
                if occupied:
                    raise ValueError(f"destination already has {source['weapon_set']} · {source['slot']} "
                                     f"{source['variant']}; remove it explicitly before connecting")
                chosen.append(source)

            now = time.time()
            for source in chosen:
                # A linked binding has its own stable identity and customizable
                # compatibility/weight, while clip_id stays owned by the donor.
                binding_id = (f"binding__npc__{target_npc}__{source['weapon_set']}__"
                              f"{source['slot']}__{int(source['variant']):02d}")
                db.execute(
                    """INSERT INTO monster_animation_bindings
                       (id,monster_slug,slot,variant,clip_id,weight,playback_speed_percent,
                        looped,priority,created_at,updated_at,weapon_set,disarm,compatible_sets)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (binding_id, target_npc, source['slot'], source['variant'], source['clip_id'],
                     source['weight'], source['playback_speed_percent'], source['looped'],
                     source['priority'], now, now, source['weapon_set'], source['disarm'],
                     source['compatible_sets']),
                )

        self.export()
        return {'connected': len(chosen), 'sourceNpc': source_npc, 'targetNpc': target_npc,
                'snapshot': self.snapshot(target_npc)}

    def connected_dependents(self, owner: str) -> list[dict]:
        """All consumers outside the source actor (for delete preflight)."""
        if self.kind != 'npc':
            return []
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                """SELECT b.monster_slug,b.slot,b.variant,b.weapon_set,c.id AS clip_id
                   FROM monster_animation_bindings b
                   JOIN monster_animation_clips c ON c.id=b.clip_id
                   WHERE c.monster_slug=? AND b.monster_slug<>c.monster_slug
                   ORDER BY b.monster_slug,b.weapon_set,b.slot,b.variant""",
                (owner,),
            )]
