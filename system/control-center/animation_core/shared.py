"""Explicit shared Character Animation bindings.

Stores references to source bindings, never duplicates a publication or clip. A
family share is only exported if the source publication is current. A target's
own binding always has precedence over common. Cross-rig validation is
conservative: identical binds are generic; the two canonical human jump slots
may use compatible locomotion skeletons with differing unused face/grip sockets.
"""
from __future__ import annotations
import json
import sqlite3
from .common import _now

NON_BODY_BONES = frozenset({'face_mouth', 'face_mustache', 'weapon_grip_l'})
# Social gestures are body poses. Weapon-display gestures must retain grip validation.
BODY_BASE_STATES = frozenset({'idle', 'walk', 'run', 'jump_start', 'jump_loop', 'fall', 'land'})
WEAPON_SOCIAL_STATES = frozenset({'atk', 'victory'})


def compatible_rigs(source_bones, target_bones, *, scope, slot):
    first = {b['name']: b for b in source_bones}
    second = {b['name']: b for b in target_bones}
    if len(first) != len(source_bones) or len(second) != len(target_bones) or first.keys() != second.keys():
        raise ValueError('shared animation: incompatible rig bone inventory')
    jump = scope == 'base' and slot in ('jump_start', 'jump_loop')
    body = (scope == 'base' and slot in BODY_BASE_STATES) or scope == 'social'
    ignored = set(NON_BODY_BONES) if body else set()
    if scope == 'social' and slot in WEAPON_SOCIAL_STATES:
        ignored.discard('weapon_grip_l')
    for name, bone in first.items():
        other = second[name]
        if name in ignored:
            if bone['parent'] != other['parent']:
                raise ValueError('shared jump: incompatible socket hierarchy for '+name)
            continue
        if bone['parent'] != other['parent'] or len(bone['matrix']) != 16 or len(other['matrix']) != 16:
            raise ValueError('shared animation: incompatible bind hierarchy for '+name)
        if max(abs(a-b) for a,b in zip(bone['matrix'],other['matrix'])) > 2e-5:
            raise ValueError('shared animation: incompatible bind pose for '+name)
    return 'locomotion-core' if jump else ('body-core' if body else 'full-bind')


class AnimationSharedMixin:
    def validate_common_source(self, db, family: str, selected_character: str,
                               scope: str, slot: str) -> str:
        """Validate the *authoring rig* selected for a human_common file.

        Filename identity alone cannot prove FBX keyframe compatibility; we
        require compatible target rigs and preserve a clear authoring contract.
        """
        rigs = self._family_rigs(db, family)
        if selected_character not in rigs:
            raise ValueError('selected authoring rig unavailable for common animation')
        policy = ''
        for target_bones in rigs.values():
            policy = compatible_rigs(rigs[selected_character], target_bones,
                                     scope=scope, slot=slot)
        return policy

    def shared_rows(self, family: str = '') -> list[dict]:
        query = """SELECT s.family,s.scope,s.weapon_set,s.slot,s.variant,s.source_binding_id,
                   b.character_id AS source_character,b.clip_id,b.weight,b.looped,b.priority,
                   c.asset_id,c.sha256,c.published_sha256,c.prepared_path,c.moderation_state,c.name
                   FROM animation_shared_bindings s
                   JOIN animation_bindings b ON b.id=s.source_binding_id
                   JOIN animation_clips c ON c.id=b.clip_id
                   WHERE (?='' OR s.family=?) ORDER BY s.family,s.scope,s.weapon_set,s.slot,s.variant"""
        with self.connect() as db:
            rows=[dict(row) for row in db.execute(query,(family,family))]
        for row in rows:
            row['status']='PUBLISHED' if self._status(row)=='PUBLISHED' and str(row.get('asset_id') or '').isdigit() and str(row.get('moderation_state') or '').lower()=='approved' else 'UNAVAILABLE'
            row['looped']=bool(row['looped'])
            row['sourceFilename']=(row['source_character'] + '_' + row['name'] + '.rbxm') \
                if str(row['source_character']).endswith('_common') else ''
            row['animationId']='rbxassetid://'+str(row['asset_id']) if row['status']=='PUBLISHED' else ''
        return rows

    @staticmethod
    def _family_rigs(db, family: str) -> dict[str, list[dict]]:
        """Read authored rig bones for every character in this family, once."""
        result = {}
        for character in db.execute('SELECT id FROM characters WHERE race=?', (family,)):
            character_id = character['id']
            rig = db.execute(
                "SELECT metadata_json FROM character_component_records WHERE kind='rig' AND id=?",
                (character_id,),
            ).fetchone()
            if rig is None:
                raise ValueError('target rig metadata unavailable: ' + character_id)
            result[character_id] = json.loads(rig['metadata_json'])['bones']
        return result

    def _require_shareable(self, row: dict, rigs: dict[str, list[dict]]) -> str:
        """Identical validation for picker and mutation; no optimistic UI approvals."""
        if row['scope'] not in ('base', 'social', 'emotions', 'weapon'):
            raise ValueError('unsupported shared animation scope')
        if (not str(row.get('asset_id') or '').isdigit()
                or self._status(row) != 'PUBLISHED'
                or str(row.get('moderation_state') or '').lower() != 'approved'):
            raise ValueError('share requires a currently published animation')
        source_id = row['character_id']
        if source_id not in rigs and source_id != str(row.get('race') or '') + '_common':
            raise ValueError('source rig metadata unavailable: ' + source_id)
        if not rigs:
            raise ValueError('no registered target rigs for this family')
        source_bones = rigs.get(source_id, next(iter(rigs.values())))
        policy = ''
        for target_bones in rigs.values():
            policy = compatible_rigs(source_bones, target_bones,
                                     scope=row['scope'], slot=row['slot'])
        if not policy:
            raise ValueError('no registered target rigs for this family')
        return policy

    def shared_candidates(self, family: str) -> list[dict]:
        """Eligible published clips from *both* genders for the Common selection list.

        Incompatible approved clips remain visible with a disabled reason. The
        selection is a reference to a binding, never a copied publication.
        """
        if not family:
            return []
        with self.connect() as db:
            rows = [dict(r) for r in db.execute('''
                SELECT b.id AS binding_id,b.character_id,b.scope,b.weapon_set,b.slot,
                       b.variant,b.weight,b.looped,b.priority,c.name,c.asset_id,
                       c.sha256,c.published_sha256,c.prepared_path,c.moderation_state,
                       COALESCE(ch.gender, 'common') AS gender FROM animation_bindings b
                JOIN animation_clips c ON c.id=b.clip_id
                LEFT JOIN characters ch ON ch.id=b.character_id
                WHERE ch.race=? OR b.character_id=?
                ORDER BY b.scope,b.weapon_set,b.slot,b.variant,gender,b.id
            ''', (family, family + '_common'))]
            selected = {(r['scope'], r['weapon_set'], r['slot'], r['variant']): r['source_binding_id']
                        for r in db.execute('''
                            SELECT scope,weapon_set,slot,variant,source_binding_id
                            FROM animation_shared_bindings WHERE family=?
                        ''', (family,))}
            if not any(
                str(row.get('asset_id') or '').isdigit()
                and self._status(row) == 'PUBLISHED'
                and str(row.get('moderation_state') or '').lower() == 'approved'
                for row in rows
            ):
                return []
            try:
                rigs = self._family_rigs(db, family)
                rig_error = ''
            except (ValueError, TypeError, KeyError, sqlite3.OperationalError) as error:
                rigs, rig_error = {}, str(error)
        result = []
        for row in rows:
            # A draft or replaced asset isn't a usable source in the picker.
            if (not str(row.get('asset_id') or '').isdigit()
                    or self._status(row) != 'PUBLISHED'
                    or str(row.get('moderation_state') or '').lower() != 'approved'):
                continue
            reason = rig_error
            policy = ''
            if not reason:
                try:
                    policy = self._require_shareable(dict(row, race=family), rigs)
                except (ValueError, TypeError, KeyError) as error:
                    reason = str(error)
            key = (row['scope'], row['weapon_set'], row['slot'], row['variant'])
            result.append({
                'bindingId': row['binding_id'],
                'sourceCharacter': row['character_id'], 'sourceGender': row['gender'],
                'scope': row['scope'], 'weaponSet': row['weapon_set'],
                'slot': row['slot'], 'variant': row['variant'],
                'name': (row['character_id'] + '_' + row['name'])
                        if row['character_id'].endswith('_common') else row['name'],
                'assetId': str(row['asset_id']),
                'ready': not bool(reason), 'reason': reason, 'compatibility': policy,
                'selected': selected.get(key) == row['binding_id'],
                'replacesSource': selected.get(key, ''),
            })
        return result

    def set_shared(self, binding_id: str, enabled: bool) -> dict:
        with self.connect() as db:
            row=db.execute("""SELECT b.*,c.asset_id,c.sha256,c.published_sha256,c.prepared_path,c.moderation_state,
                                     COALESCE(ch.race, '') AS race,
                                     COALESCE(ch.gender, 'common') AS gender
                              FROM animation_bindings b
                              JOIN animation_clips c ON c.id=b.clip_id
                              LEFT JOIN characters ch ON ch.id=b.character_id WHERE b.id=?""",(binding_id,)).fetchone()
            if not row:
                raise ValueError('unknown animation binding: '+binding_id)
            row=dict(row); family=str(row['race']).strip().lower()
            if not family and row['character_id'].endswith('_common'):
                family = row['character_id'][:-len('_common')]
                row['race'] = family
            if enabled:
                self._require_shareable(row, self._family_rigs(db, family))
                db.execute("""INSERT INTO animation_shared_bindings(family,scope,weapon_set,slot,variant,source_binding_id,created_at)
                              VALUES(?,?,?,?,?,?,?) ON CONFLICT(family,scope,weapon_set,slot,variant)
                              DO UPDATE SET source_binding_id=excluded.source_binding_id""",
                           (family,row['scope'],row['weapon_set'],row['slot'],row['variant'],binding_id,_now()))
            else:
                db.execute('DELETE FROM animation_shared_bindings WHERE family=? AND source_binding_id=?',(family,binding_id))
        self.export()
        return self.snapshot(row['character_id'])
